from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils


class AddressDetails:

    def __init__(self, *, account_address, description, tags, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry, {
                    'account_address': account_address,
                    'description': description,
                    'tags': tags
                }
            )

        self.account_address = account_address
        self.description = description
        self.tags = tags

    def __eq__(self, other):
        if not isinstance(other, AddressDetails):
            return False

        return (self.account_address == other.account_address and
                self.description == other.description and
                self.tags == other.tags)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')

        return types_utils.ClassSpec(
            name='AddressDetails',
            docstring='''
                Address details gives a rich description of an address.
                The tags can be shared between addresses and even different accounts.
            ''',
            public_attributes=[
                types_utils.ValueSpec(
                    name='account_address',
                    type='str',
                    docstring='''
                        The account address the details describe.
                    '''
                ),
                types_utils.ValueSpec(
                    name='description',
                    type='str',
                    docstring='''
                        The human-readable description of the address.
                    '''
                ),
                types_utils.ValueSpec(
                    name='tags',
                    type='List[str]',
                    docstring='''
                        The list of string tags related to the described address.
                    '''
                )
            ],
            constructor=types_utils.ConstructorSpec(
                docstring='',
                args=[
                    types_utils.ValueSpec(
                        name='account_address',
                        type='str',
                        docstring='''
                        The account address the details describe.
                    '''
                    ),
                    types_utils.ValueSpec(
                        name='description',
                        type='str',
                        docstring='''
                        The human-readable description of the address.
                    '''
                    ),
                    types_utils.ValueSpec(
                        name='tags',
                        type='List[str]',
                        docstring='''
                        The list of string tags related to the described address.
                    '''
                    )
                ]
            )
        )
