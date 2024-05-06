from decimal import Decimal
import re
import pytz
from datetime import datetime, timezone, timedelta
from library.credit_card.tests.utils.common.common import parse_datetime

LOCAL_UTC_OFFSET = 0


def offset_datetime(year, month=None, day=None, hour=0, minute=0, second=0, microsecond=0):
    return datetime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        microsecond=microsecond,
        tzinfo=timezone(offset=timedelta(hours=LOCAL_UTC_OFFSET)),
    )


def check_postings_correct_after_simulation(res, posting):
    post_cbi = posting["client_batch_id"]
    post_time = posting["value_timestamp"]
    post_cti = posting["posting_instructions"][0]["client_transaction_id"]
    post_amt = posting["posting_instructions"][0]["custom_instruction"]["postings"][0]["amount"]
    for result in res:
        if result["result"]["posting_instruction_batches"]:
            pib = result["result"]["posting_instruction_batches"][0]
            res_cbi = pib["client_batch_id"]
            res_time = pytz.utc.localize(parse_datetime(pib["value_timestamp"]))
            for res_instruction in pib["posting_instructions"]:
                res_cti = res_instruction["client_transaction_id"]
                res_amt = res_instruction["committed_postings"][0]["amount"]
                if (
                    post_cbi == res_cbi
                    and re.search(post_cti, res_cti)
                    and post_time == res_time
                    and Decimal(post_amt) == Decimal(res_amt)
                ):
                    return True
    return False
