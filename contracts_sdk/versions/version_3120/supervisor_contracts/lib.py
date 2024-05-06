from abc import abstractmethod
from functools import lru_cache
from typing import Dict

from . import types as supervisor_contract_types
from ...version_3110.supervisor_contracts import lib as v3110_lib
from ..common import lib as common_lib
from ....utils import feature_flags, symbols, types_utils


types_registry = supervisor_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v3110_lib.VaultFunctionsABC):
    @abstractmethod
    def instruct_notification(
        self,
        notification_type: str,
        notification_details: Dict[str, str],
    ):
        pass

    @abstractmethod
    def get_posting_instructions_by_supervisee(self):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        spec.public_methods["instruct_notification"] = types_utils.MethodSpec(
            name="instruct_notification",
            docstring="""
                    Instructs the publishing of a notification.
                    **Only available in version 3.12+**
                """,
            args=[
                types_utils.ValueSpec(
                    name="notification_type",
                    type="str",
                    docstring="The `type` of notification to be published.",
                ),
                types_utils.ValueSpec(
                    name="notification_details",
                    type="Dict[str, str]",
                    docstring="""
                            The information (key-value pairs of data) to be published
                            with the notification.
                        """,
                ),
            ],
            examples=[
                types_utils.Example(
                    title="How to instruct a notification event",
                    code="""
                            notification_types = ['NOTIFICATION_TYPE']

                            def post_posting_code(postings, effective_date):
                                vault.instruct_notification(
                                    notification_type='NOTIFICATION_TYPE',
                                    notification_details={
                                        "key": "value",
                                    }
                                )
                        """,
                )
            ],
        )
        if feature_flags.is_fflag_enabled(feature_flags.PRE_POSTING_SUPERVISION):
            spec.public_methods["get_posting_instructions_by_supervisee"] = types_utils.MethodSpec(
                name="get_posting_instructions_by_supervisee",
                docstring="""
                    Retrieves a Dict mapping supervisee
                    accountID ->
                    [PostingInstructionBatch](../types/#classes-PostingInstructionBatch)
                    for all [PostingInstructions](../types/#classes-PostingInstruction)
                    within the postings argument received by the Supervisor hook.
                    For each entry within the Dict, the PostingInstructionBatch will only contain
                    [PostingInstructions](../types/#classes-PostingInstruction) that target
                    the key supervisee accountID.
                    If no postings received in the Supervisor hook execution target a particular
                    supervised account, the entry under that supervisee's accountID entry will be
                    None.
                    **NOTE: Only supported within pre_posting_code and post_posting_code hooks.**
                    **Only available in version 3.12+**
                """,
                args=[],
                return_value=types_utils.ReturnValueSpec(
                    docstring="""
                        Dict containing supervisee account ID to filtered
                        [PostingInstructionBatch](../types/#classes-PostingInstructionBatch)
                        containing only those
                        [PostingInstructions](../types/#classes-PostingInstruction) that target
                        the key supervisee accountID.
                    """,
                    type="Dict[str, Optional[PostingInstructionBatch]]",
                ),
                examples=[
                    types_utils.Example(
                        title="Convert Supervisor postings argument to a mapping of "
                        "accountID -> PostingInstructionBatch",
                        code="""
                            # Supervisor supervises accounts A, B, C.
                            # Supervisor invoked with postings argument containing
                            # PostingInstructions A1, A2, B1
                            # targeting accounts A, B.
                            # postings = PostingInstructionBatch[A1, A2, B1]

                            supervisee_to_postings = vault.get_posting_instructions_by_supervisee()
                            # supervisee_to_postings will be a Dict containing:
                            # "A" -> PostingInstructionBatch[A1, A2]
                            # "B" -> PostingInstructionBatch[B1]
                            # "C" -> None

                            account_A_postings = supervisee_to_postings["A"]
                            """,
                    )
                ],
            )
        return spec
