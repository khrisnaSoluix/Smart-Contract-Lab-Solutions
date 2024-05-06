from functools import lru_cache

from ....version_390.common import types as common_types_390
from .....utils import symbols


class EventTypesGroup(common_types_390.EventTypesGroup):
    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        spec = super()._spec(language_code)

        spec.docstring += f"""

**From version 3.10**
Any events within an EventTypesGroup that are supervised with [flexible supervision](/reference/contracts/supervisor_overview/#flexible_supervision) will no
longer be considered a part of that EventTypesGroup. This means that:
* Supervised events are **not** guaranteed to be executed in the order
 specified by the original EventTypesGroup. However, unsupervised events are
 guaranteed to be executed in the specified order.
* Vault skips the original event (defined in the Smart Contract) and the Supervisor
 Contract event runs instead. Since an account is not aware of whether it is being
 supervised, the original event will report a success and the next event
 in the EventTypesGroup will be triggered immediately
 (regardless of whether the Supervisor Contract event has run).
"""  # noqa: E501

        return spec
