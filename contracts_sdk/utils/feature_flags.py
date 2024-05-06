from functools import wraps
import unittest

from . import feature_flags_config

# A list of feature flags used in the Contracts Language library.
PRE_POSTING_SUPERVISION = "TM_68040_CONTRACTS_PRE_POSTING_SUPERVISION"
CONTRACTS_NOTIFICATION_EVENT = "TM_66923_CONTRACTS_NOTIFICATION_EVENT"
MOVE_SCX_PARSE_ENDPOINT_TO_CP = "TM_70887_MOVE_SCX_PARSE_ENDPOINT_TO_CP"
PRE_PARAM_CHANGE_HOOK_VALIDATION = "TM_70781_PRE_PARAM_CHANGE_HOOK_VALIDATION"
MOVE_CX_PARSE_ENDPOINT_TO_CP = "TM_71209_MOVE_CX_PARSE_ENDPOINT_TO_CP"
CONFIGURATION_HIERARCHY_PARAMETERS = "CPP_786_CONFIGURATION_HIERARCHY_PARAMETERS"
CONTRACTS_SIMULATION_LOGGING = "TM_71633_CONTRACTS_SIMULATION_LOGGING"


CONTRACT_LANGUAGE_FFLAGS = [
    PRE_POSTING_SUPERVISION,
    CONTRACTS_NOTIFICATION_EVENT,
    MOVE_SCX_PARSE_ENDPOINT_TO_CP,
    PRE_PARAM_CHANGE_HOOK_VALIDATION,
    MOVE_CX_PARSE_ENDPOINT_TO_CP,
    CONFIGURATION_HIERARCHY_PARAMETERS,
    CONTRACTS_SIMULATION_LOGGING,
]


def is_fflag_enabled(feature_flag: str) -> bool:
    """
    Checks if a feature flag is enabled within the CONTRACT_FFLAGS_CONFIG.
    Returns a boolean to indicate if the checked flag is enabled.
    """
    return feature_flags_config.CONTRACT_FFLAGS_CONFIG.get(feature_flag, False)


def skip_if_not_enabled(feature_flag: str):
    """
    Decorator that skips a given test if the passed feature flag is not enabled
    within the CONTRACT_FFLAGS_CONFIG.
    """

    def skip_wrapper(test):
        @wraps(test)
        def wrapped_test(test_instance, *args, **kwargs):
            if not is_fflag_enabled(feature_flag):
                raise unittest.SkipTest(f"Feature flag {feature_flag} not enabled in environment.")
            else:
                return test(test_instance, *args, **kwargs)

        return wrapped_test

    return skip_wrapper
