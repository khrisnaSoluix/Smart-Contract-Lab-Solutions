# constants - test_wallet
POSTING_BATCH_ACCEPTED = "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED"
POSTING_BATCH_REJECTED = "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED"
BASE_WALLET_FLAG_DEF_FOLDER = "library/wallet/flag_definitions"
AUTO_TOP_UP_WALLET_FLAG = "AUTO_TOP_UP_WALLET"

# constants - test_wallet_product_schedules
SCHEDULE_TAGS_DIR = "library/wallet/account_schedule_tags/schedules_tests/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are paused
DEFAULT_TAGS = {
    "PAUSED_ZERO_OUT_DAILY_SPEND_TAG": PAUSED_SCHEDULE_TAG,
}

# wallet template parameters
wallet_template_params = {
    "zero_out_daily_spend_hour": "23",
    "zero_out_daily_spend_minute": "59",
    "zero_out_daily_spend_second": "59",
}
