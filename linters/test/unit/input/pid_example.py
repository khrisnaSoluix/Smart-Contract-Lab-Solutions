# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal

# contracts api
from contracts_api import CustomInstruction, Phase, Posting, PostingInstructionsDirective

PostingInstructionsDirective(
    posting_instructions=[
        CustomInstruction(
            postings=[
                Posting(
                    credit=True,
                    amount=Decimal(1),
                    denomination="denomination",
                    account_id="account_id",
                    account_address="address",
                    asset="asset",
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal(1),
                    denomination="denomination",
                    account_id="account_id",
                    account_address="address",
                    asset="asset",
                    phase=Phase.COMMITTED,
                ),
            ]
        )
    ]
)
