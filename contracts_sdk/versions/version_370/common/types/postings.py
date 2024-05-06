from functools import lru_cache

from ....version_360.common.types import postings as postings360
from .....utils import symbols, types_utils


class TransactionCode:
    def __init__(self, *, domain, family, subfamily, _from_proto=False):
        arguments = {
            "domain": domain,
            "family": family,
            "subfamily": subfamily,
        }
        if not _from_proto:
            self._spec().assert_constructor_args(self._registry, arguments)

        missing = [k for k, v in arguments.items() if not v]
        if missing:
            raise TypeError(f"TransactionCode missing required argument(s): {missing}")

        self.domain = domain
        self.family = family
        self.subfamily = subfamily

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="TransactionCode",
            docstring="""
                ISO20022 Bank Transaction Code with information about payment domain, family and subfamily.
                For further information, see the [Postings API reference](/reference/postings_api/#key_components-what_is_a_posting_instruction).
                **Only available in version 3.7.0+**.
            """,  # noqa E501
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="", args=cls._public_attributes(language_code)
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="domain",
                type="str",
                docstring="""
                    Business area of the transaction.
                """,
            ),
            types_utils.ValueSpec(
                name="family",
                type="str",
                docstring="""
                    A family within the domain.
                """,
            ),
            types_utils.ValueSpec(
                name="subfamily",
                type="str",
                docstring="""
                    Sub-product family within a specific family.
                """,
            ),
        ]


class PostingInstruction(postings360.PostingInstruction):
    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        super_spec = super()._spec(language_code)
        super_spec.constructor.args["transaction_code"] = types_utils.ValueSpec(
            name="transaction_code",
            type="Optional[TransactionCode]",
            docstring="""
                ISO20022 Bank Transaction Code field; a set of properties to identify the
                underlying transaction. **Only available in version 3.7.0+**.
            """,
        )
        super_spec.public_methods[
            "balances"
        ].docstring = """
            **Not available on Supervisor PostingInstruction objects**
            Returns the net balance changes caused by this PostingInstruction.
        """

        return super_spec

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        super_public_atts = super()._public_attributes(language_code)
        super_public_atts.append(
            types_utils.ValueSpec(
                name="transaction_code",
                type="Optional[TransactionCode]",
                docstring="""
                    ISO20022 Bank Transaction Code field; a set of properties to identify the
                    underlying transaction. **Only available in version 3.7.0+**.
                """,
            )
        )

        return super_public_atts


class PostingInstructionBatch(postings360.PostingInstructionBatch):
    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        super_spec = super()._spec(language_code)
        super_spec.public_methods[
            "balances"
        ].docstring = """
            **Not available on Supervisor PostingInstructionBatch objects**
            Returns the net balance changes caused by this PostingInstructionBatch.
        """
        return super_spec
