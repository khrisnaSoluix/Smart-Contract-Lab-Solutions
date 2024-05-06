from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils


class FlagTimeseries(types_utils.Timeseries('bool', 'flag', lambda *_: False)):

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')

        return types_utils.merge_class_specs(
            derived_spec=types_utils.ClassSpec(
                name='FlagTimeseries',
                docstring='''
                    A timeseries for the active status for a given flag definition.
                    If the flag definition does not exist the timeseries will be empty
                    and .at() will always return False.
                '''
            ),
            base_spec=super()._spec(language_code)
        )
