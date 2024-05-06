# flake8: noqa
# standard libs
from datetime import datetime

# contracts api
from contracts_api import fetch_account_data, requires

# inception sdk
import inception_sdk.tools.renderer.test.feature.test_resources.test_replace_decorator_constants.feature_1 as feature_1  # noqa: E501

api = "4.0.0"


def custom_decorator(*args, **kwargs):
    def wrapper_func(*args, **kwargs):
        pass

    return wrapper_func


EVENT_2 = "EVENT_2"
BOF_2 = "bif_2"

PIF_2 = "pif_2"
PIF_3 = "pif_3"
PIF_4 = "pif_4"
ALL_LOCAL_PIF = [PIF_2, PIF_3, PIF_4]

CUSTOM_DATA = "CUSTOM_DATA"

chained_bof = feature_1.BOF_1
twice_chained_bof = chained_bof


# feature_1.EVENT_1 should be replaced
@requires(
    event_type=feature_1.EVENT_1,
    parameters=True,
    balances="latest",
    last_execution_datetime=[feature_1.EVENT_1],
)
# all decorator constants should be replaced
@fetch_account_data(
    balances=[BOF_2],
    postings=[feature_1.CHAINED_PIF_1, *feature_1.CHAINED_PIFS, *ALL_LOCAL_PIF],
    event_type=EVENT_2,
)
def scheduled_code(event_type: str, effective_date: datetime) -> None:
    pass


# CUSTOM_DATA should not be replaced since custom decorators ignored
@custom_decorator(data=CUSTOM_DATA)
# chained_bof AND twice_chained_bof should be replaced with the value of feature_1.BOF_1
# i.e. "bif_1"
@fetch_account_data(balances=[chained_bof])
@fetch_account_data(balances={"v1": [chained_bof], "v2": [twice_chained_bof]})
def post_posting_code():
    pass
