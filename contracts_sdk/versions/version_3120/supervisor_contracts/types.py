from functools import lru_cache

from ...version_3110.supervisor_contracts.types import *  # noqa: F401, F403
from ...version_3110.supervisor_contracts import types as types3110
from ..common.types import (
    SupervisedHooks,
    SupervisionExecutionMode,
    HookDirectives,
    InstructAccountNotificationDirective,
)
from ....utils import types_utils, symbols
from ....utils.feature_flags import (
    is_fflag_enabled,
    PRE_POSTING_SUPERVISION,
    CONTRACTS_NOTIFICATION_EVENT,
)


class SmartContractDescriptor(types3110.SmartContractDescriptor):
    def __init__(
        self,
        *,
        alias,
        smart_contract_version_id,
        supervise_post_posting_hook=False,
        supervised_hooks=None
    ):
        self._spec().assert_constructor_args(self._registry, {"supervised_hooks": supervised_hooks})
        super().__init__(
            alias=alias,
            smart_contract_version_id=smart_contract_version_id,
            supervise_post_posting_hook=supervise_post_posting_hook,
        )
        self.supervised_hooks = supervised_hooks

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SmartContractDescriptor",
            docstring="""
                **Only available in version 3.4+**
                Each Supervisor Contract must declare the Smart Contracts that it supervises. Using
                the Smart Contract Descriptor object, a Product Version Id is declared with an alias
                that is used throughout the Supervisor Contract to refer to this Smart Contract
                Product Version.
                **Only available in version 3.7+:**
                An optional flag can be used to declare that a supervisee will have
                its post_posting_code hook supervised.
                **Only available in version 3.12+:**
                The supervised_hooks attribute can be populated to declare that a supervisee will
                have additional hooks supervised, with specific
                [SupervisionExecutionModes](/reference/contracts/apis_3XX/supervisor_contracts_api_reference3XX/types/#enums-SupervisionExecutionMode).
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SmartContractDescriptor",
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        super_public_attr = super()._public_attributes(language_code)
        super_public_attr.append(
            types_utils.ValueSpec(
                name="supervised_hooks",
                type="Optional[SupervisedHooks]",
                docstring="""
                    This attribute can be populated with a
                    [SupervisedHooks](../types/#classes-SupervisedHooks)
                    value to specify which hooks are supervised, and with which execution mode.
                """,
            ),
        )
        return super_public_attr


def types_registry():
    TYPES = types3110.types_registry()
    if is_fflag_enabled(feature_flag=PRE_POSTING_SUPERVISION):
        TYPES["SupervisedHooks"] = SupervisedHooks
        TYPES["SupervisionExecutionMode"] = SupervisionExecutionMode
        TYPES["SmartContractDescriptor"] = SmartContractDescriptor
    if is_fflag_enabled(feature_flag=CONTRACTS_NOTIFICATION_EVENT):
        TYPES["InstructAccountNotificationDirective"] = InstructAccountNotificationDirective
        TYPES["HookDirectives"] = HookDirectives
    return TYPES
