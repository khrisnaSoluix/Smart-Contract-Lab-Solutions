from functools import lru_cache

from ....version_310.common.types import postings as postings310, PostingInstructionType

from .....utils import symbols
from .....utils import types_utils
from .....utils.exceptions import InvalidSmartContractError


class PostingInstructionBatch(postings310.PostingInstructionBatch):
    def balances(self):
        raise NotImplementedError("Missing implementation")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        spec = super()._spec(language_code)
        spec.public_methods["balances"].args["exclude_advice"] = types_utils.ValueSpec(
            name="exclude_advice",
            type="bool",
            docstring=(
                "If set to `True`, the method will return only the aggregated balances for "
                "instructions in which the advice flag is **not** set to `True`. Available on "
                "versions 3.2.0+."
            ),
        )

        return spec


class PostingInstruction(postings310.PostingInstruction):
    def __init__(self, **kwargs):
        if not kwargs.get("_from_proto", False):
            self._spec().assert_constructor_args(
                self._registry, {"advice": kwargs.get("advice", False)}
            )

            # Raise an error if advice attribute is set on a PostingInstruction with
            # PostingInstructionType that does not support it.
            type_arg = kwargs.get("type", "")
            advice_arg = kwargs.get("advice")
            if type_arg not in {
                PostingInstructionType.AUTHORISATION,
                PostingInstructionType.AUTHORISATION_ADJUSTMENT,
                PostingInstructionType.HARD_SETTLEMENT,
            }:
                if advice_arg is not None:
                    raise InvalidSmartContractError(f"Advice can not be set for {type_arg}")

        super().__init__(**kwargs)

        # Default advice attribute to false if it is not supplied
        # to the PostingInstructions of PostingInstructionTypes that support it.
        if self.type in [
            PostingInstructionType.AUTHORISATION,
            PostingInstructionType.AUTHORISATION_ADJUSTMENT,
            PostingInstructionType.HARD_SETTLEMENT,
        ]:
            if not hasattr(self, "advice"):
                self.advice = False

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        spec = super()._spec(language_code)
        spec.constructor.args["advice"] = types_utils.ValueSpec(
            name="advice",
            type="Optional[bool]",
            docstring="""
                Where present, this indicates that the Smart Contract should skip balance checks
                for this Posting Instruction. For the advice flag to be set in the Posting
                Instruction object, it must be supported in the specific type Posting
                Instruction object in the Core API. This defaults to false if supported by the
                PostingInstructionType but not supplied. Only present when type is one of
                PostingInstructionType.AUTHORISATION,
                PostingInstructionType.AUTHORISATION_ADJUSTMENT or
                PostingInstructionType.HARD_SETTLEMENT. Available in versions 3.2.0+.
            """,
        )

        return spec

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        public_attr = super()._public_attributes(language_code)
        public_attr.append(
            types_utils.ValueSpec(
                name="advice",
                type="Optional[bool]",
                docstring="""
                    Where present, this indicates that the Smart Contract should skip balance checks
                    for this Posting Instruction. For the advice flag to be set in the Posting
                    Instruction object, it must be supported in the specific type Posting
                    Instruction object in the Core API. This defaults to false if supported by the
                    PostingInstructionType but not supplied. Only present when type is one of
                    PostingInstructionType.AUTHORISATION,
                    PostingInstructionType.AUTHORISATION_ADJUSTMENT or
                    PostingInstructionType.HARD_SETTLEMENT. Available in versions 3.2.0+.
                """,
            )
        )

        return public_attr
