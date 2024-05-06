from functools import lru_cache

from .....utils import symbols, types_utils


class CalendarEvent:

    def __init__(self, *, id, calendar_id, start_timestamp, end_timestamp, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry, {
                    'id': id,
                    'calendar_id': calendar_id,
                    'start_timestamp': start_timestamp,
                    'end_timestamp': end_timestamp
                }
            )

        self.id = id
        self.calendar_id = calendar_id
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')

        return [
            types_utils.ValueSpec(
                name='id',
                type='str',
                docstring='''
                    Uniquely identifies the Calendar Event in the Vault Calendar resource.
                '''
            ),
            types_utils.ValueSpec(
                name='calendar_id',
                type='str',
                docstring='''
                    The ID of the Calendar that this Calendar Event belongs to.
                '''
            ),
            types_utils.ValueSpec(
                name='start_timestamp',
                type='datetime',
                docstring='''
                    The logical timestamp at which the Calendar Event starts taking effect.
                '''
            ),
            types_utils.ValueSpec(
                name='end_timestamp',
                type='datetime',
                docstring='''
                    The logical timestamp at which the Calendar Event stops taking effect.
                '''
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')

        return types_utils.ClassSpec(
            name='CalendarEvent',
            docstring='''
                A unique event resource defined in the Vault Calendar.
                **Only available in version 3.7.0+**.
            ''',
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring='',
                args=cls._public_attributes(language_code),
            )
        )


class CalendarEvents(types_utils.TypedList('CalendarEvent')):

    def __init__(self, *, calendar_events=(), _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry, {
                    'calendar_events': calendar_events,
                }
            )

        super().__init__(calendar_events, _from_proto)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')

        return types_utils.ClassSpec(
            name='CalendarEvents',
            docstring='A list of CalendarEvent objects. **Only available in version 3.7.0+**',
            constructor=types_utils.ConstructorSpec(
                docstring='',
                args=[
                    types_utils.ValueSpec(
                        name='calendar_events',
                        type='List[CalendarEvent]',
                        docstring='''
                            A list of CalendarEvent objects.
                        '''
                    ),
                ]
            )
        )
